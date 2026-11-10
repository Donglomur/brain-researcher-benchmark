"""Trusted full-cohort admission and view issuer. No candidate receives this object.
All authentic methods are future-only. No arrays/identities are loaded by inert controls.
"""
import hashlib
from collections import Counter
import hmac
from pathlib import Path
from .common import need, digest, load, read, pin, probabilities, number, verify
from .spec import PEOPLE, LABELS, WINDOWS, FAMILIES, DIMS, DOMAIN, INERT, cases, slots, concept_group, bucket


def opaque(secret, *values):
    return hmac.new(secret, '|'.join(str(x) for x in values).encode(), hashlib.sha256).hexdigest()


def summary_payload(value):
    need(set(value) == {'classes', 'query'} and len(value['classes']) == 27 and len(value['query']) == 8,
         'Complete D payload')
    floats = list(value['query']); counts = []
    for pair in value['classes']:
        need(type(pair) is list and len(pair) == 2, 'Binary class summaries in [0,1] order')
        for c in pair:
            need(set(c) == {'count', 'mean', 'variance'} and len(c['mean']) == len(c['variance']) == 8,
                 'Complete summary coordinates')
            need(type(c['count']) is int and c['count'] > 0, 'Both classes supported')
            counts.append(c['count']); floats.extend(c['mean']); floats.extend(c['variance'])
            need(all(float(v) >= 0 for v in c['variance']), 'Population variances nonnegative')
    need(len(floats) == 872 and len(counts) == 54, 'No shortened summary')
    for x in floats:
        need(type(x) is str and number(float(x)) and format(float(x), '.17g') == x,
             'Exact 17-significant-digit roundtrippable serialization')
    return value


class FeatureIssuer:
    """Concrete issuer over an independently admitted full extracted feature release.
    JSON transport is explicit; its substantial copying/RSS costs remain unqualified G17.
    """
    def __init__(self, admission, root, secret, authorization_pin):
        need(admission['domain'] == DOMAIN and admission['execution_selection'] == authorization_pin,
             'Exact external execution selection required')
        need(len(secret) == 32, 'Private issuer secret')
        self.secret = secret; self.root = Path(root); self.domain = DOMAIN
        self.generation = admission['generation']; self.admission = admission
        need(admission['release_bridge']['status'] == 'QUALIFIED' and
             admission['clock_geometry']['status'] == 'QUALIFIED' and
             admission['preprocessing']['status'] == 'QUALIFIED', 'Unclosed source/clock/native gates')
        self.rows = load(self.root / admission['roster']['path'], 64 << 20,
                         {k: admission['roster'][k] for k in ('bytes', 'sha256')})
        self.annotations = load(self.root / admission['labels']['path'], 4 << 20,
                                {k: admission['labels'][k] for k in ('bytes', 'sha256')})
        need(self.annotations['names'] == list(LABELS), 'Original 27 categories')
        ann = self.annotations['concepts']; need(len(ann) == 1854, 'All concepts')
        self.labels = {r['concept']: r['labels'] for r in ann}
        need(set(self.labels) == set(range(1, 1855)), 'Exact concept identity')
        for y in self.labels.values():
            need(type(y) is list and len(y) == 27 and all(type(v) is int and v in (0, 1) for v in y), 'Original overlapping labels')
        need(len(self.rows) == 108192, 'All original trial dispositions')
        expected_counts = {'exp': 22248, 'repeat': 2400, 'catch': 2400}
        for person in PEOPLE:
            person_rows = [r for r in self.rows if r['person'] == person]
            need(len(person_rows) == 27048 and {r['epoch_index'] for r in person_rows} == set(range(27048)),
                 'Complete exact person epochs')
            need(all(sum(r['trial_type'] == t for r in person_rows) == n for t, n in expected_counts.items()),
                 'No source-trial omission or relabeling')
            need({r['session'] for r in person_rows} == set(range(1, 13)) and
                 all({r['run'] for r in person_rows if r['session'] == s} == set(range(1, 11)) for s in range(1, 13)),
                 'All original sessions/runs')
        self.experimental = [r for r in self.rows if r['trial_type'] == 'exp']
        need(len(self.experimental) == 88992 and len({(r['person'], r['image']) for r in self.experimental}) == 88992,
             'Full experimental identity set')
        need(all(r['concept'] in self.labels for r in self.experimental), 'Annotation join')
        self.experimental.sort(key=lambda r: (PEOPLE.index(r['person']), r['epoch_index']))
        for person in PEOPLE:
            rs = [r for r in self.experimental if r['person'] == person]
            need(Counter(r['concept'] for r in rs) == Counter({c: 12 for c in range(1,1855)}), 'All 12 exemplars per concept')
            need(Counter((r['session'],r['concept']) for r in rs) == Counter({(s,c): 1 for s in range(1,13) for c in range(1,1855)}), 'Exactly one experimental exemplar per concept in every session')
        self.index = {(r['person'], r['epoch_index']): i for i, r in enumerate(self.experimental)}
        self.private = {}; public_slots = []; used = set()
        for c in cases():
            train = [i for i, r in enumerate(self.experimental) if r['person'] != c['person'] and
                     r['session'] != c['session'] and concept_group(r['concept']) != c['fold']]
            query = [i for i, r in enumerate(self.experimental) if r['person'] == c['person'] and
                     r['session'] == c['session'] and concept_group(r['concept']) == c['fold']]
            need(train and query and not used.intersection(query), 'Nonempty disjoint outer support'); used.update(query)
            for w in WINDOWS:
                for a in FAMILIES:
                    sid = opaque(secret, 'slot', digest(c), w, a)
                    # Per-slot query aliases prevent unintended cross-view/cross-query identity channels.
                    qids = {i: opaque(secret, sid, 'query', self.experimental[i]['image']) for i in query}
                    pairs = sorted((qid, i) for i, qid in qids.items())
                    training = sorted(train, key=lambda i: opaque(secret, digest(c), 'train', i))
                    self.private[sid] = {'training': training, 'query': pairs, 'case': c, 'window': w, 'arm': a}
                    public_slots.append({'id': sid, 'logical': {'case': c, 'window': w, 'arm': a},
                                         'query_ids': [qid for qid, _ in pairs]})
        need(used == set(range(88992)), 'Exactly-once source trial query coverage')
        self.panel = {'domain': DOMAIN, 'generation': self.generation, 'slots': public_slots,
                      'experimental_rows': 88992, 'recorded_rows': 108192,
                      'target_commitment': admission['target_commitment']}
        self.features = None

    def _open_features(self):
        import numpy as np
        if self.features is not None: return
        # No pickle or arbitrary object loading. Exact source pins precede native access.
        self.features = {}
        for name, rec in self.admission['features'].items():
            path = self.root / rec['path']
            verify(path, {k: rec[k] for k in ('bytes', 'sha256')}, rec['bytes'])
            a = np.load(path, mmap_mode='r', allow_pickle=False)
            need(a.dtype == np.dtype('<f4') and list(a.shape) == rec['shape'], 'Exact projected array layout')
            self.features[name] = a
        need(self.features['visual'].shape == (22248, 103), 'Full visual bank')
        for family in ('ocular', 'neural'):
            need(self.features[family].shape == (88992, 5, DIMS[family]), 'Full neural/ocular bank')
        self.image_index = {im: i for i, im in enumerate(self.admission['image_order'])}
        need(len(self.image_index) == 22248 and set(self.image_index) == {r['image'] for r in self.experimental}, 'Exact image bank')

    def _families(self, indices, view):
        import numpy as np
        self._open_features(); out = {}; w = list(WINDOWS).index(view['window'])
        for family in FAMILIES[view['arm']]:
            if family == 'visual':
                values = self.features[family][[self.image_index[self.experimental[i]['image']] for i in indices]]
            else: values = self.features[family][indices, w, :]
            need(np.isfinite(values).all(), 'No signal-row deletion/nonfinite features')
            out[family] = values.tolist()
        return out

    def training(self, sid):
        v = self.private[sid]; indices = v['training']; case = digest(v['case'])
        groups = {key: [] for key in ('person', 'session', 'concept', 'image')}
        inner = []
        for i in indices:
            row = self.experimental[i]
            for key in groups: groups[key].append(opaque(self.secret, case, 'group', key, row[key]))
            inner.append({'person': groups['person'][-1],
                          'session_bucket': bucket('NEURAL054-inner-session-v1:', row['session'], 3),
                          'concept_bucket': bucket('NEURAL054-inner-concept-v1:', row['concept'], 3)})
        return {'families': self._families(indices, v), 'labels': [self.labels[self.experimental[i]['concept']] for i in indices],
                'groups': groups, 'inner': inner, 'label_order': list(LABELS),
                'inner_policy': 'All 3 people x 3 session buckets x 3 concept buckets; AND validation, exclude all three for train'}

    def query(self, sid, qid):
        v = self.private[sid]; matches = [i for q, i in v['query'] if q == qid]
        need(len(matches) == 1, 'Exactly one admitted query')
        return {'id': qid, 'families': self._families(matches, v), 'label_order': list(LABELS)}

    def protected_targets(self):
        # Only controller's post-global-seal grader invokes this method.
        return {sid: {qid: self.labels[self.experimental[i]['concept']] for qid, i in v['query']}
                for sid, v in self.private.items()}

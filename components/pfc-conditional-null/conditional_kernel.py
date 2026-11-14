"""Exact conditional-null moments for a fixed PFC map and complete cohort.

No file, RNG, scientific-library or fitting operations. The reference is a
prospective conditional computation, not archived biological ground truth.
"""
from collections import Counter, defaultdict
from fractions import Fraction
import math

ROUTES = ('gaoRois', 'dataRois')
REFS = ('refall', 'refPFC')
ENCODINGS = ('nolays', 'lays', 'laydepth')
SUBSETS = ('deepRois', 'nolayRois', 'layeredRois', 'deepSupRois')
FAMILIES = tuple('/'.join((r, p, s)) for r in ROUTES for p in REFS for s in ENCODINGS)
CONTEXTS = tuple('/'.join((r, p, s)) for r in ROUTES for p in REFS for s in SUBSETS)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def rational(value):
    need(type(value) is list and len(value) == 2 and all(type(x) is int for x in value),
         'rational must contain two exact integers')
    need(value[1] > 0 and max(abs(value[0]), value[1]).bit_length() <= 512,
         'bounded positive rational denominator')
    result = Fraction(*value)
    need([result.numerator, result.denominator] == value, 'canonical reduced rational')
    return result


def pair(value):
    return [value.numerator, value.denominator]


def moments(N, a, b):
    """One task: independent attribute permutations, fixed margins."""
    need(all(type(x) is int for x in (N, a, b)) and 0 <= a <= N and 0 <= b <= N,
         'hypergeometric integer margins')
    if N == 0:
        return Fraction(0), Fraction(0)
    mean = Fraction(a * b, N)
    variance = Fraction(0) if N == 1 else Fraction(a*b*(N-a)*(N-b), N*N*(N-1))
    return mean, variance


def validate_packet(packet, *, expected_units, expected_recordings):
    need(packet['schema'] == 'PFC_FULL99_FIXED_MAP_PACKET_V1', 'packet schema')
    units, families, contexts = packet['units'], packet['families'], packet['contexts']
    need(len(units) == expected_units and len({u['id'] for u in units}) == expected_units,
         'complete unit support')
    need(len(packet['records']) == expected_recordings and
         len({r['id'] for r in packet['records']}) == expected_recordings,
         'complete source recording support, including zero-fit recordings')
    record_roster = {r['id']:(r['animal'],r['task']) for r in packet['records']}
    need([f['key'] for f in families] == list(FAMILIES), 'all twelve ordered null families')
    need([c['key'] for c in contexts] == list(CONTEXTS), 'all sixteen ordered ROI contexts')
    animals = sorted({u['animal'] for u in units})
    need(len(animals) >= 3 and animals == packet['animals'], 'complete witnessed fitting-animal roster')
    for f in families:
        need(f['labels'] == sorted(set(f['labels'])) and len(f['labels']) > 0, 'source lexical label axes')
    records = {}
    for u in units:
        need(type(u['category']) is int and 0 <= u['category'] < 8, 'fixed eight-category coordinate')
        need(len(u['labels']) == 12 and all(type(v) is int for v in u['labels']), 'twelve membership slots')
        for j, label in enumerate(u['labels']):
            need(-1 <= label < len(families[j]['labels']), 'family membership axis')
            need(label >= 0 or '/refPFC/' in families[j]['key'], 'full reference contains every unit')
        need(all(type(u[k]) is str and 0 < len(u[k]) <= 256 for k in ['id','animal','recording','task']),
             'finite unit metadata')
        key = u['recording']
        need(record_roster.get(key) == (u['animal'],u['task']), 'unit joins witnessed source recording')
        need(key not in records or records[key] == (u['animal'], u['task']), 'recording group/task conflict')
        records[key] = (u['animal'], u['task'])
    for c in contexts:
        need(type(c['family']) is int and 0 <= c['family'] < 12, 'context parent family')
        indices = c['indices']
        need(indices == sorted(set(indices)) and len(indices) > 0 and
             all(type(i) is int and 0 <= i < len(families[c['family']]['labels']) for i in indices),
             'fixed full-cohort ROI panel')
        if c['hierarchy'] is not None:
            need(c['key'].startswith('gaoRois/') and c['key'].split('/')[-1] in ('deepRois','nolayRois')
                 and len(c['hierarchy']) == len(indices), 'all four hierarchy coordinates')
            need(all(type(v) in (int,float) and math.isfinite(v) or v in ('NaN','+Infinity','-Infinity')
                     for v in c['hierarchy']), 'explicit hierarchy nonfinite state')
    need(sum(c['hierarchy'] is not None for c in contexts) == 4, 'all four Gao contexts')
    return animals


def case_keys(packet):
    return ['full'] + ['without:' + a for a in packet['animals']]


def reconstruct(packet, deleted_animal=None, tick=lambda: None):
    """All12 families; same deleted animal applies jointly to every family."""
    need(deleted_animal is None or deleted_animal in packet['animals'], 'declared animal deletion')
    selected = [u for u in packet['units'] if u['animal'] != deleted_animal]
    result = []
    for fi, family in enumerate(packet['families']):
        tick()
        nr = len(family['labels'])
        count = [[0] * 8 for _ in range(nr)]
        groups = defaultdict(lambda: {'N': 0, 'a': Counter(), 'b': [0]*8})
        for u in selected:
            label = u['labels'][fi]
            if label < 0:
                continue
            category = u['category']
            count[label][category] += 1
            g = groups[u['task']]
            g['N'] += 1; g['a'][label] += 1; g['b'][category] += 1
        means, variances = [], []
        for row in range(nr):
            mu, var = [], []
            for category in range(8):
                pieces = [moments(g['N'], g['a'][row], g['b'][category]) for g in groups.values()]
                mu.append(pair(sum((v[0] for v in pieces), Fraction(0))))
                var.append(pair(sum((v[1] for v in pieces), Fraction(0))))
            means.append(mu); variances.append(var)
        result.append({'key': family['key'], 'counts': count, 'mean': means, 'variance': variances})
    return {'case': 'full' if deleted_animal is None else 'without:' + deleted_animal,
            'families': result}


def validate_submission_case(case, packet, expected_key):
    need(set(case) == {'case','families'} and case['case'] == expected_key, 'complete ordered case')
    need(type(case['families']) is list and len(case['families']) == 12, 'complete twelve-family submission')
    for got, expected in zip(case['families'], packet['families']):
        need(set(got) == {'key','counts','mean','variance'} and got['key'] == expected['key'], 'family identity')
        n = len(expected['labels'])
        for field in ('counts','mean','variance'):
            need(type(got[field]) is list and len(got[field]) == n and
                 all(type(row) is list and len(row) == 8 for row in got[field]), 'complete cell support')
        for row in got['counts']:
            need(all(type(v) is int and 0 <= v <= len(packet['units']) for v in row), 'bounded nonnegative count')
        for field in ('mean','variance'):
            for row in got[field]:
                for v in row:
                    x = rational(v)
                    need(0 <= x <= len(packet['units']) ** (1 if field == 'mean' else 2),
                         'finite conditional moment bounds')


def enrich(family):
    result = []
    for counts, means, variances in zip(family['counts'], family['mean'], family['variance']):
        row = []
        for observed, mu, var in zip(counts, means, variances):
            variance = rational(var)
            # Zero null variance is undefined even when the numerator is zero.
            row.append(None if not variance else float(Fraction(observed)-rational(mu))/math.sqrt(float(variance)))
        result.append(row)
    return result


def moment_errors(candidate, reference):
    out = []
    for got, expected in zip(candidate['families'], reference['families']):
        fields = {}
        for field in ('counts','mean','variance'):
            delta = [abs(Fraction(a)-Fraction(b)) if field == 'counts' else abs(rational(a)-rational(b))
                     for ra, rb in zip(got[field], expected[field]) for a,b in zip(ra,rb)]
            # Do not form the potentially enormous LCM of arbitrary participant
            # denominators. Equality and maximum remain exact; the descriptive
            # average sums already-exact coordinate errors in binary64.
            fields[field] = {'mean_absolute_error_binary64': math.fsum(float(x) for x in delta)/len(delta),
                             'max_absolute_error_exact': pair(max(delta)), 'unequal_cells': sum(x != 0 for x in delta)}
        out.append({'family': expected['key'], 'cells': len(expected['counts'])*8, **fields})
    return out


def adjusted_rand(left, right):
    """Label-invariant agreement; exact rational contingency arithmetic."""
    need(len(left) == len(right) and len(left) >= 2, 'partition support')
    choose2 = lambda n: n*(n-1)//2
    table, a, b = Counter(zip(left,right)), Counter(left), Counter(right)
    n = choose2(len(left)); aa = sum(map(choose2,a.values())); bb = sum(map(choose2,b.values()))
    index = sum(map(choose2,table.values())); expected = Fraction(aa*bb,n)
    denominator = Fraction(aa+bb,2)-expected
    return Fraction(1) if denominator == 0 else (Fraction(index)-expected)/denominator


def hierarchy_sensitivity(full, deletions, animal_count):
    """Exhaustive influence, deliberately no population confidence interval."""
    need(len(deletions) == animal_count, 'all animal deletions retained')
    out = {}
    for key, baseline in full.items():
        out[key] = []
        for category, base in enumerate(baseline):
            values = [d[key][category] for d in deletions]
            finite = [v for v in values if v is not None]
            wanted = 1 if category == 0 else -1 if category == 5 else None
            out[key].append({'category': category+1, 'full': base, 'defined_deletions': len(finite),
                'all_animals': animal_count, 'range': [min(finite),max(finite)] if finite else None,
                'max_abs_change': max(abs(v-base) for v in finite) if finite and base is not None else None,
                'predeclared_direction': wanted,
                'complete_direction_stability': (base is not None and wanted*base > 0 and
                    all(wanted*v > 0 for v in finite) and len(finite)==animal_count)
                    if wanted is not None else None})
    return out

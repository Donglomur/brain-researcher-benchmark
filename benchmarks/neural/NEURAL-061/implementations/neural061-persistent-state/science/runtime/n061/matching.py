"""Prespecified sampling, never called during the source-only construction phase."""
from bisect import bisect_right
from collections import defaultdict, Counter
import random
import hashlib
from .contracts import need, canonical, RATE_EDGES_HZ, BUDGETS, MATCH_SEEDS, REALIZATIONS

def rng_for(scope):
    return random.Random(int.from_bytes(hashlib.sha256(canonical(scope)).digest(), 'big'))

def stratum(u):
    # Exact same probe/QC category and octave rate band; residual rates are reported.
    return (u.probe, u.qc_neural, u.qc_alignment, u.label, bisect_right(RATE_EDGES_HZ, u.rate)-1)

def eligible(u):
    return u.qc_neural == 'PASS' and u.qc_alignment == 'PASS' and u.label == 1.0 and u.rate > 0

def select(rows, region, k, seed, realization, region_family):
    need(k in BUDGETS and seed in MATCH_SEEDS and realization in REALIZATIONS, 'fixed sampling contract')
    need(rows and len({u.session for u in rows}) == 1, 'one actual recording')
    need(region in region_family,'prespecified grey-matter family')
    session = rows[0].session
    groups = defaultdict(list)
    for u in rows:
        if eligible(u) and u.region in region_family: groups[stratum(u)].append(u)
    labels = {u.index: u.region for u in rows}
    if realization == 'stratified_anatomy_shuffle':
        for s in sorted(groups):
            pool = sorted(groups[s], key=lambda u: u.index)
            values = [u.region for u in pool]
            rng_for(['anatomy-shuffle', session, seed, s]).shuffle(values)
            labels.update(zip((u.index for u in pool), values, strict=True))
    triples = []; capacity = []
    for s in sorted(groups):
        rr = [u for u in groups[s] if labels[u.index] == region]
        cc = [u for u in groups[s] if labels[u.index] != region]
        generator = rng_for(['triples', session, region, seed, realization, s])
        generator.shuffle(rr); generator.shuffle(cc)
        local=[];remaining=list(cc)
        for r in rr:
            candidates=[u for u in remaining if max(u.rate,r.rate)/min(u.rate,r.rate)<=1.25]
            if len(candidates)<2:continue
            # Fixed random order breaks equally qualified matching choices without outcomes.
            c,b=candidates[:2];remaining.remove(c);remaining.remove(b)
            local.append((r.index,c.index,b.index))
        capacity.append({'stratum': s, 'region': len(rr), 'other': len(cc), 'triples': len(local), 'max_rate_ratio':1.25})
        triples.extend(local)
    if len(triples) < k:
        return {'status': 'unavailable', 'reason': 'insufficient_exact_matched_support',
                'session': session, 'region': region, 'budget': k, 'seed': seed,
                'realization': realization, 'capacity': capacity, 'required': k, 'available': len(triples)}
    rng_for(['choose-triples', session, region, seed, realization]).shuffle(triples)
    selected = triples[:k]; r = tuple(x[0] for x in selected); c = tuple(x[1] for x in selected); b = tuple(x[2] for x in selected)
    lookup = {u.index: u for u in rows}
    need(len(set(r+c+b)) == 3*k, 'disjoint actual unit axes')
    counts = [Counter(stratum(lookup[i]) for i in v) for v in (r, c, b)]
    need(counts[0] == counts[1] == counts[2], 'exact probe/rate-band/quality balance')
    return {'status': 'complete', 'session': session, 'region': region, 'budget': k,
            'seed': seed, 'realization': realization, 'triples': tuple(selected), 'capacity': capacity,
            'arms': {'R': r, 'C': c, 'B': b, 'BR': b+r, 'BC': b+c, 'ZERO': ()},
            'balance': {'R_rates': tuple(lookup[i].rate for i in r), 'C_rates': tuple(lookup[i].rate for i in c),
                        'B_rates': tuple(lookup[i].rate for i in b), 'strata': tuple(stratum(lookup[i]) for i in r)},
            'interpretation': 'matched replacement relative to co-recorded non-region population; observational'}
